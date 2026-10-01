using System;
using System.Data;
using System.Configuration;
using System.Collections;
using System.Web;
using System.Web.Security;
using System.Web.UI;
using System.Web.UI.WebControls;
using System.Web.UI.WebControls.WebParts;
using System.Web.UI.HtmlControls;
using System.Data.SqlClient;
using EBS.Classes;
using EBS_Common.Classes.Misc;
using EBS_Common.Classes;
using System.Collections.Generic;

public partial class Quality_And_Safety_Drills_frmHSE_Drill_Record_Improvement : System.Web.UI.Page
{
    # region User defined variables
    //protected Common_DataRetrival _Common_DataRetrival;
    string strConString = "";
    protected DataSet Ds;
    string ErrorString = "";
    SqlConnection Conn;
    SqlDataAdapter Da;
    int intUser_Id;
    Button[] btnEnableDisable;
    Int16 intMenu_id;
    #endregion

    protected void Page_Load(object sender, EventArgs e)
    {        
        # region Code to Enable / Disable Button
        #region Adding buttons which needs to pass
        var list = new List<Button>();
        //list.Add(btnSearch);

        btnEnableDisable = list.ToArray();
        #endregion

        strConString = ConfigurationManager.ConnectionStrings["provider_default"].ToString();

        #region 1st Parameter is always Menu Id
        string strScramble = Request.QueryString["A"];
        string strdeCrypt = clsMiscellaneous.decryptQueryString(strScramble.Replace(" ", "+"));

        string strMonthly_HSE_Returns_Hdr_Id = Request.QueryString["B"];///Copy the HDR ID in this
        tbDrill_Record_Hdr_Id_Hidden.Value = clsMiscellaneous.decryptQueryString(strMonthly_HSE_Returns_Hdr_Id.Replace(" ", "+"));


        //string strDrill_Dt = Request.QueryString["C"];
        //tbDrill_Dt_Id_Hidden.Value = clsMiscellaneous.decryptQueryString(strDrill_Dt.Replace(" ", "+"));

        intMenu_id = Convert.ToInt16(strdeCrypt);
        intUser_Id = Convert.ToInt16(Session["User_Id"].ToString());
        # endregion

        if (!IsPostBack)
        {
            EBS_Common.clsUserRights.GetUserRights(ref btnEnableDisable, intUser_Id, intMenu_id, strConString, "Add");

            FillGrid();
            tbPostbackFlag_Hidden.Value = ""; 
        }
        
        if (tbPostbackFlag_Hidden.Value == "SEARCH")
        {
            FillGrid();
            tbPostbackFlag_Hidden.Value = ""; 
        }
        #endregion
    }


    protected void FillGrid()
    {
        ClearMe(false);

        EBS_Common.clsUserRights.GetUserRights(ref btnEnableDisable, intUser_Id, intMenu_id, strConString, "Search");

        Conn = new SqlConnection(strConString);
        try
        {
            if (Conn.State == ConnectionState.Closed)
                Conn.Open();

            Ds = new DataSet();
            Da = new SqlDataAdapter(OI.Def + "Prc_HSE_Drill_Record_Improvement", Conn);
            Da.SelectCommand.CommandType = CommandType.StoredProcedure;
            Da.SelectCommand.Parameters.Add("@Drill_Record_Hdr_Id", SqlDbType.SmallInt).Value = Convert.ToInt16(tbDrill_Record_Hdr_Id_Hidden.Value);
            Da.SelectCommand.Parameters.Add("@Record_Status", SqlDbType.VarChar).Value = "Select_By_Drill_Record_Hdr_Id";
            Da.Fill(Ds, "DataForEdit");
 
            DataTable contacts = Ds.Tables["DataForEdit"];
            if (contacts.Rows.Count > 0)
            {
                grdImprovement.DataSource = contacts;
                grdImprovement.DataBind();

            }
            else
            {
                contacts.Rows.Add(contacts.NewRow());
                grdImprovement.DataSource = contacts;
                grdImprovement.DataBind();

                int TotalColumns = grdImprovement.Rows[0].Cells.Count;
                grdImprovement.Rows[0].Cells.Clear();
                grdImprovement.Rows[0].Cells.Add(new TableCell());
                grdImprovement.Rows[0].Cells[0].ColumnSpan = TotalColumns;
                grdImprovement.Rows[0].Cells[0].Text = "No Record Found";
            }
            grdImprovement.FooterRow.FindControl("txtDrill_Rec_Improvement_Desc").Focus();


        }
        catch (SqlException sqlexep)
        {
            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(sqlexep, ref Conn);
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
            return;
        }
        catch (Exception exep)
        {
            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(exep, ref Conn);
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Error", ErrorString);
            return;
        }
        finally
        {
            if (Conn.State == ConnectionState.Open)
            {
                Conn.Close();
            }

        }

    }
 
   
    private void ClearMe(bool blnClearMainId)
    {
        if (blnClearMainId == true)
        {
          
        }         

        grdImprovement.DataSource = null;
        grdImprovement.DataBind();
         
        EBS_Common.clsUserRights.GetUserRights(ref btnEnableDisable, intUser_Id, intMenu_id, strConString, "Clear");
    }
 

    protected void btnClear_Click(object sender, EventArgs e)
    {
        ClearMe(true);
    } 

    protected void grdImprovement_RowCommand(object sender, GridViewCommandEventArgs e)
    {
        if (e.CommandName.Equals("Insert"))
        {
            try
            {
               
                TextBox txtDrill_Rec_Improvement_Desc = (TextBox)grdImprovement.FooterRow.FindControl("txtDrill_Rec_Improvement_Desc");

                clsHSE_Drill_Record_Improvement _ObjMaster = new clsHSE_Drill_Record_Improvement(strConString);
                _ObjMaster.Drill_Record_Hdr_Id = Convert.ToInt16(tbDrill_Record_Hdr_Id_Hidden.Value);              
                _ObjMaster.Drill_Rec_Improvement_Desc = txtDrill_Rec_Improvement_Desc.Text.Trim();

                _ObjMaster.Cr_User_Id = Convert.ToInt16(Session["User_Id"].ToString());
                _ObjMaster.InsertMe();

                

                if ((_ObjMaster.ErrorString != "") && (_ObjMaster.ErrorString != null))
                {
                    throw new Exception(_ObjMaster.ErrorString);
                }
                //ScriptManager.RegisterStartupScript(this, this.GetType(), "MSG1", "<script>callpopup_ipwidth('Record inserted', 2000,'',220);</script>", false);

               FillGrid();
            }

            catch (SqlException sqlexep)
            {

                ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(sqlexep, ref Conn);
                ClientScript.RegisterClientScriptBlock(this.GetType(), "Err_Update", ErrorString);

                return;
            }
            catch (Exception exep)
            {

                ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(exep, ref Conn);
                ClientScript.RegisterClientScriptBlock(this.GetType(), "Err_Update1", ErrorString);

                return;
            }
            finally
            {
            }
        }

        if (e.CommandName == "cmdDelete")
        {
            try
            {
                clsHSE_Drill_Record_Improvement _ObjMaster = new clsHSE_Drill_Record_Improvement(strConString);

                Int16 intDrill_Rec_Improvement_Id = Convert.ToInt16(e.CommandArgument);
                _ObjMaster.Drill_Rec_Improvement_Id = intDrill_Rec_Improvement_Id;
                _ObjMaster.DeleteMe();
                

                if ((_ObjMaster.ErrorString != "") && (_ObjMaster.ErrorString != null))
                {
                    throw new Exception(_ObjMaster.ErrorString);
                }
                ScriptManager.RegisterStartupScript(this, this.GetType(), "MSG1", "<script>callpopup_ipwidth('Record Deleted', 2000,'',220);</script>", false);
                FillGrid();
            }
            catch (SqlException sqlexep)
            {
                ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(sqlexep, ref Conn);
                ClientScript.RegisterClientScriptBlock(this.GetType(), "Err_Update1", ErrorString);
                return;
            }
            catch (Exception exep)
            {
                ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(exep, ref Conn);
                ClientScript.RegisterClientScriptBlock(this.GetType(), "Err_Update1", ErrorString);
                return;
            }
            finally
            {
            }
        }
    }
     

    protected void grdImprovement_RowUpdating(object sender, GridViewUpdateEventArgs e)
    {
        try
        {
            Label lblId = (Label)grdImprovement.Rows[e.RowIndex].FindControl("lblId");
            
            TextBox txtEdit_Drill_Rec_Improvement_Desc = (TextBox)grdImprovement.Rows[e.RowIndex].FindControl("txtEdit_Drill_Rec_Improvement_Desc");

            clsHSE_Drill_Record_Improvement _ObjMaster = new clsHSE_Drill_Record_Improvement(strConString);
            
            _ObjMaster.Drill_Rec_Improvement_Id = Convert.ToInt16(lblId.Text);            
            _ObjMaster.Drill_Rec_Improvement_Desc = txtEdit_Drill_Rec_Improvement_Desc.Text.Trim();
            _ObjMaster.Mod_User_Id = Convert.ToInt16(Session["User_Id"].ToString());
            _ObjMaster.UpdateMe();
             
            if ((_ObjMaster.ErrorString != "") && (_ObjMaster.ErrorString != null))
            {
                throw new Exception(_ObjMaster.ErrorString);
            }

            ScriptManager.RegisterStartupScript(this, this.GetType(), "MSG1", "<script>callpopup_ipwidth('Record Updated', 2000,'',220);</script>", false);
            grdImprovement.EditIndex = -1;
            FillGrid();
              
        }
        catch (SqlException sqlexep)
        {
            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(sqlexep, ref Conn);
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Err_Update", ErrorString);
            return;
        }
        catch (Exception exep)
        {

            ErrorString = new EBS_Common.Classes.clsExceptionHandling().getErrorScript(exep, ref Conn);
            ClientScript.RegisterClientScriptBlock(this.GetType(), "Err_Update1", ErrorString);
            return;
        }
        finally
        {
        }
    }

    protected void grdImprovement_RowCancelingEdit(object sender, GridViewCancelEditEventArgs e)
    {
        grdImprovement.EditIndex = -1;
        FillGrid(); 
    }

    protected void grdImprovement_RowEditing(object sender, GridViewEditEventArgs e)
    {
        grdImprovement.EditIndex = e.NewEditIndex;
        FillGrid();
    }  
}




